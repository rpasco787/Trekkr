# Stats API Endpoints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GET /api/v1/stats/countries and GET /api/v1/stats/regions endpoints that return user travel statistics with coverage percentages.

**Architecture:** Query-on-the-fly approach joining user_cell_visits → h3_cells → regions tables. Coverage calculated as cells_visited / land_cells_total_resolution8. Follows existing MapService pattern.

**Tech Stack:** FastAPI, SQLAlchemy (raw SQL with text()), Pydantic v2, pytest

---

## Task 1: Create Pydantic schemas for stats endpoints

**Files:**
- Create: `backend/schemas/stats.py`

**Step 1: Create the stats schema file**

Create `backend/schemas/stats.py`:

```python
"""Pydantic schemas for stats endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StatsQueryParams(BaseModel):
    """Query parameters for stats endpoints."""

    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CountryStatResponse(BaseModel):
    """Statistics for a single country."""

    code: str  # ISO 3166-1 alpha-3 (e.g., "USA")
    name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime


class CountriesStatsResponse(BaseModel):
    """Response for /stats/countries endpoint."""

    total_countries_visited: int
    countries: list[CountryStatResponse]


class RegionStatResponse(BaseModel):
    """Statistics for a single region/state."""

    code: str  # ISO 3166-2 (e.g., "US-CA")
    name: str
    country_code: str  # ISO 3166-1 alpha-3
    country_name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime


class RegionsStatsResponse(BaseModel):
    """Response for /stats/regions endpoint."""

    total_regions_visited: int
    regions: list[RegionStatResponse]
```

**Step 2: Verify syntax**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && python -c "from schemas.stats import StatsQueryParams, CountriesStatsResponse, RegionsStatsResponse; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add backend/schemas/stats.py
git commit -m "$(cat <<'EOF'
feat(schemas): add stats endpoint Pydantic schemas

Add request/response schemas for GET /api/v1/stats/countries and
GET /api/v1/stats/regions endpoints:
- StatsQueryParams: sort_by, order, limit, offset
- CountryStatResponse/CountriesStatsResponse
- RegionStatResponse/RegionsStatsResponse

EOF
)"
```

---

## Task 2: Create StatsService with get_countries() method

**Files:**
- Create: `backend/services/stats_service.py`

**Step 1: Create the stats service file**

Create `backend/services/stats_service.py`:

```python
"""Stats service for retrieving user travel statistics."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session


class StatsService:
    """Service for stats-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_countries(
        self,
        sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at",
        order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get countries the user has visited with coverage statistics.

        Args:
            sort_by: Field to sort by
            order: Sort order (asc/desc)
            limit: Max number of results
            offset: Pagination offset

        Returns:
            dict with 'total_countries_visited' and 'countries' list
        """
        # Validate sort_by to prevent SQL injection
        valid_sort_fields = {
            "coverage_pct": "coverage_pct",
            "first_visited_at": "first_visited_at",
            "last_visited_at": "last_visited_at",
            "name": "c.name",
        }
        sort_field = valid_sort_fields.get(sort_by, "last_visited_at")
        order_dir = "DESC" if order == "desc" else "ASC"

        # Get total count first
        count_query = text("""
            SELECT COUNT(DISTINCT c.id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country c ON hc.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """)
        total = self.db.execute(count_query, {"user_id": self.user_id}).scalar() or 0

        # Get paginated results with coverage
        data_query = text(f"""
            SELECT
                c.iso3 AS code,
                c.name,
                COUNT(ucv.id) AS cells_visited,
                COALESCE(c.land_cells_total_resolution8, 1) AS cells_total,
                MIN(ucv.first_visited_at) AS first_visited_at,
                MAX(ucv.last_visited_at) AS last_visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country c ON hc.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY c.id, c.iso3, c.name, c.land_cells_total_resolution8
            ORDER BY {sort_field} {order_dir}
            LIMIT :limit OFFSET :offset
        """)

        rows = self.db.execute(data_query, {
            "user_id": self.user_id,
            "limit": limit,
            "offset": offset,
        }).fetchall()

        countries = []
        for row in rows:
            coverage_pct = row.cells_visited / row.cells_total if row.cells_total > 0 else 0.0
            countries.append({
                "code": row.code,
                "name": row.name,
                "coverage_pct": round(coverage_pct, 6),
                "first_visited_at": row.first_visited_at,
                "last_visited_at": row.last_visited_at,
            })

        return {
            "total_countries_visited": total,
            "countries": countries,
        }
```

**Step 2: Verify syntax**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && python -c "from services.stats_service import StatsService; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add backend/services/stats_service.py
git commit -m "$(cat <<'EOF'
feat(service): add StatsService.get_countries()

Query-on-the-fly approach to calculate country statistics:
- Joins user_cell_visits -> h3_cells -> regions_country
- Calculates coverage_pct from cells_visited / land_cells_total
- Supports sorting by coverage, name, or visit timestamps
- Pagination with limit/offset

EOF
)"
```

---

## Task 3: Add get_regions() method to StatsService

**Files:**
- Modify: `backend/services/stats_service.py`

**Step 1: Add get_regions method**

Add this method to the `StatsService` class in `backend/services/stats_service.py`:

```python
    def get_regions(
        self,
        sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at",
        order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get regions/states the user has visited with coverage statistics.

        Args:
            sort_by: Field to sort by
            order: Sort order (asc/desc)
            limit: Max number of results
            offset: Pagination offset

        Returns:
            dict with 'total_regions_visited' and 'regions' list
        """
        # Validate sort_by to prevent SQL injection
        valid_sort_fields = {
            "coverage_pct": "coverage_pct",
            "first_visited_at": "first_visited_at",
            "last_visited_at": "last_visited_at",
            "name": "s.name",
        }
        sort_field = valid_sort_fields.get(sort_by, "last_visited_at")
        order_dir = "DESC" if order == "desc" else "ASC"

        # Get total count first
        count_query = text("""
            SELECT COUNT(DISTINCT s.id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state s ON hc.state_id = s.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """)
        total = self.db.execute(count_query, {"user_id": self.user_id}).scalar() or 0

        # Get paginated results with coverage
        data_query = text(f"""
            SELECT
                CONCAT(c.iso2, '-', s.code) AS code,
                s.name,
                c.iso3 AS country_code,
                c.name AS country_name,
                COUNT(ucv.id) AS cells_visited,
                COALESCE(s.land_cells_total_resolution8, 1) AS cells_total,
                MIN(ucv.first_visited_at) AS first_visited_at,
                MAX(ucv.last_visited_at) AS last_visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state s ON hc.state_id = s.id
            JOIN regions_country c ON s.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY s.id, s.code, s.name, s.land_cells_total_resolution8, c.id, c.iso2, c.iso3, c.name
            ORDER BY {sort_field} {order_dir}
            LIMIT :limit OFFSET :offset
        """)

        rows = self.db.execute(data_query, {
            "user_id": self.user_id,
            "limit": limit,
            "offset": offset,
        }).fetchall()

        regions = []
        for row in rows:
            coverage_pct = row.cells_visited / row.cells_total if row.cells_total > 0 else 0.0
            regions.append({
                "code": row.code,
                "name": row.name,
                "country_code": row.country_code,
                "country_name": row.country_name,
                "coverage_pct": round(coverage_pct, 6),
                "first_visited_at": row.first_visited_at,
                "last_visited_at": row.last_visited_at,
            })

        return {
            "total_regions_visited": total,
            "regions": regions,
        }
```

**Step 2: Verify syntax**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && python -c "from services.stats_service import StatsService; print('get_regions' in dir(StatsService) and 'OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add backend/services/stats_service.py
git commit -m "$(cat <<'EOF'
feat(service): add StatsService.get_regions()

Query regions/states with coverage statistics:
- Joins user_cell_visits -> h3_cells -> regions_state -> regions_country
- Returns ISO 3166-2 codes (e.g., "US-CA")
- Includes parent country info
- Same sorting and pagination as get_countries()

EOF
)"
```

---

## Task 4: Create stats router with /countries endpoint

**Files:**
- Create: `backend/routers/stats.py`

**Step 1: Create the stats router file**

Create `backend/routers/stats.py`:

```python
"""Stats endpoints for retrieving user travel statistics."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Literal

from database import get_db
from models.user import User
from schemas.stats import CountriesStatsResponse, RegionsStatsResponse
from services.auth import get_current_user
from services.stats_service import StatsService


router = APIRouter()


@router.get("/countries", response_model=CountriesStatsResponse)
def get_countries_stats(
    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = Query(
        default="last_visited_at",
        description="Field to sort by",
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort order",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all countries the user has visited with coverage statistics.

    Returns country codes, names, coverage percentages, and visit timestamps.
    Supports sorting and pagination.
    """
    service = StatsService(db, current_user.id)
    result = service.get_countries(
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )

    return CountriesStatsResponse(
        total_countries_visited=result["total_countries_visited"],
        countries=result["countries"],
    )


@router.get("/regions", response_model=RegionsStatsResponse)
def get_regions_stats(
    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = Query(
        default="last_visited_at",
        description="Field to sort by",
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort order",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all regions/states the user has visited with coverage statistics.

    Returns region codes, names, parent country info, coverage percentages,
    and visit timestamps. Supports sorting and pagination.
    """
    service = StatsService(db, current_user.id)
    result = service.get_regions(
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )

    return RegionsStatsResponse(
        total_regions_visited=result["total_regions_visited"],
        regions=result["regions"],
    )
```

**Step 2: Verify syntax**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && python -c "from routers.stats import router; print('OK')"`
Expected: "OK"

**Step 3: Commit**

```bash
git add backend/routers/stats.py
git commit -m "$(cat <<'EOF'
feat(router): add stats router with countries and regions endpoints

Add GET /api/v1/stats/countries and GET /api/v1/stats/regions:
- Both require authentication
- Query params: sort_by, order, limit, offset
- Returns coverage percentages and visit timestamps

EOF
)"
```

---

## Task 5: Register stats router in main.py

**Files:**
- Modify: `backend/main.py`

**Step 1: Add import for stats router**

In `backend/main.py`, add `stats` to the import on line 9:

Change:
```python
from routers import auth, health, location, map
```

To:
```python
from routers import auth, health, location, map, stats
```

**Step 2: Register the stats router**

After line 54 (`app.include_router(map.router, ...)`), add:

```python
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
```

**Step 3: Verify syntax**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && python -c "from main import app; print([r.path for r in app.routes if 'stats' in r.path])"`
Expected: Should show routes containing 'stats'

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "$(cat <<'EOF'
feat(main): register stats router at /api/v1/stats

Add stats endpoints to the FastAPI application:
- GET /api/v1/stats/countries
- GET /api/v1/stats/regions

EOF
)"
```

---

## Task 6: Write integration tests for StatsService

**Files:**
- Create: `backend/tests/test_stats_service.py`

**Step 1: Create test file**

Create `backend/tests/test_stats_service.py`:

```python
"""Integration tests for StatsService."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from services.stats_service import StatsService
from tests.fixtures.test_data import SAN_FRANCISCO, LOS_ANGELES, TOKYO


@pytest.mark.integration
class TestStatsServiceCountries:
    """Test StatsService.get_countries() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns zero total and empty list."""
        service = StatsService(db_session, test_user.id)
        result = service.get_countries()

        assert result["total_countries_visited"] == 0
        assert result["countries"] == []

    def test_user_with_visits_returns_country_stats(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits returns country with coverage."""
        # Set up cell count for coverage calculation
        db_session.execute(text("""
            UPDATE regions_country
            SET land_cells_total_resolution8 = 1000
            WHERE id = :country_id
        """), {"country_id": test_country_usa.id})

        # Create a cell visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 1)
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "first_visited": datetime(2024, 3, 15, 10, 30),
            "last_visited": datetime(2024, 3, 15, 10, 30),
        })
        db_session.commit()

        service = StatsService(db_session, test_user.id)
        result = service.get_countries()

        assert result["total_countries_visited"] == 1
        assert len(result["countries"]) == 1

        country = result["countries"][0]
        assert country["code"] == "USA"
        assert country["name"] == "United States"
        assert country["coverage_pct"] == 0.001  # 1/1000
        assert country["first_visited_at"] == datetime(2024, 3, 15, 10, 30)

    def test_multiple_cells_same_country_aggregates(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that multiple cells in same country aggregate correctly."""
        db_session.execute(text("""
            UPDATE regions_country
            SET land_cells_total_resolution8 = 1000
            WHERE id = :country_id
        """), {"country_id": test_country_usa.id})

        # Create two cell visits
        for loc in [SAN_FRANCISCO, LOS_ANGELES]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
                VALUES (:h3_index, 8, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": loc["h3_res8"],
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": loc["longitude"],
                "lat": loc["latitude"],
            })

            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {
                "user_id": test_user.id,
                "h3_index": loc["h3_res8"],
            })
        db_session.commit()

        service = StatsService(db_session, test_user.id)
        result = service.get_countries()

        assert result["total_countries_visited"] == 1
        assert result["countries"][0]["coverage_pct"] == 0.002  # 2/1000

    def test_sorting_by_coverage(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_country_japan: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test sorting by coverage percentage."""
        # USA: 2 cells / 1000 total = 0.2%
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        # Japan: 1 cell / 100 total = 1%
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 100 WHERE id = :id
        """), {"id": test_country_japan.id})

        # Two cells in USA
        for loc in [SAN_FRANCISCO, LOS_ANGELES]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
                VALUES (:h3_index, 8, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
                ON CONFLICT DO NOTHING
            """), {
                "h3_index": loc["h3_res8"],
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": loc["longitude"],
                "lat": loc["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
                ON CONFLICT DO NOTHING
            """), {"user_id": test_user.id, "h3_index": loc["h3_res8"]})

        # One cell in Japan
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": TOKYO["h3_res8"],
            "country_id": test_country_japan.id,
            "lon": TOKYO["longitude"],
            "lat": TOKYO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": TOKYO["h3_res8"]})

        db_session.commit()

        service = StatsService(db_session, test_user.id)

        # Sort by coverage descending - Japan (1%) should be first
        result = service.get_countries(sort_by="coverage_pct", order="desc")
        assert result["countries"][0]["code"] == "JPN"
        assert result["countries"][1]["code"] == "USA"

        # Sort by coverage ascending - USA (0.2%) should be first
        result = service.get_countries(sort_by="coverage_pct", order="asc")
        assert result["countries"][0]["code"] == "USA"

    def test_pagination(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_country_japan: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test limit and offset pagination."""
        # Create visits in both countries
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": TOKYO["h3_res8"],
            "country_id": test_country_japan.id,
            "lon": TOKYO["longitude"],
            "lat": TOKYO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": TOKYO["h3_res8"]})
        db_session.commit()

        service = StatsService(db_session, test_user.id)

        # Limit to 1
        result = service.get_countries(limit=1)
        assert result["total_countries_visited"] == 2  # Total unchanged
        assert len(result["countries"]) == 1  # Only 1 returned

        # Offset by 1
        result = service.get_countries(limit=1, offset=1)
        assert len(result["countries"]) == 1

    def test_only_counts_user_cells(
        self,
        db_session,
        test_user: User,
        test_user2: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that only the requesting user's cells are counted."""
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        # User 1 has SF cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})

        # User 2 has LA cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": LOS_ANGELES["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": LOS_ANGELES["longitude"],
            "lat": LOS_ANGELES["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user2.id, "h3_index": LOS_ANGELES["h3_res8"]})
        db_session.commit()

        # User 1 should only see 1 cell (0.1% coverage)
        service = StatsService(db_session, test_user.id)
        result = service.get_countries()
        assert result["countries"][0]["coverage_pct"] == 0.001  # 1/1000


@pytest.mark.integration
class TestStatsServiceRegions:
    """Test StatsService.get_regions() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns zero total and empty list."""
        service = StatsService(db_session, test_user.id)
        result = service.get_regions()

        assert result["total_regions_visited"] == 0
        assert result["regions"] == []

    def test_user_with_visits_returns_region_stats(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits returns region with coverage."""
        # Set up cell count for coverage calculation
        db_session.execute(text("""
            UPDATE regions_state
            SET land_cells_total_resolution8 = 500
            WHERE id = :state_id
        """), {"state_id": test_state_california.id})

        # Create a cell visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 1)
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "first_visited": datetime(2024, 3, 15, 10, 30),
            "last_visited": datetime(2024, 3, 15, 10, 30),
        })
        db_session.commit()

        service = StatsService(db_session, test_user.id)
        result = service.get_regions()

        assert result["total_regions_visited"] == 1
        assert len(result["regions"]) == 1

        region = result["regions"][0]
        assert region["code"] == "US-CA"
        assert region["name"] == "California"
        assert region["country_code"] == "USA"
        assert region["country_name"] == "United States"
        assert region["coverage_pct"] == 0.002  # 1/500
```

**Step 2: Run the tests**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_stats_service.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/tests/test_stats_service.py
git commit -m "$(cat <<'EOF'
test: add StatsService integration tests

Test coverage for get_countries() and get_regions():
- Empty state handling
- Coverage percentage calculation
- Multi-cell aggregation
- Sorting by coverage_pct
- Pagination with limit/offset
- User isolation (only counts own cells)

EOF
)"
```

---

## Task 7: Write integration tests for stats router

**Files:**
- Create: `backend/tests/test_stats_router.py`

**Step 1: Create test file**

Create `backend/tests/test_stats_router.py`:

```python
"""Integration tests for stats router endpoints."""

from datetime import datetime

import pytest
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO


@pytest.mark.integration
class TestStatsCountriesEndpoint:
    """Test GET /api/v1/stats/countries endpoint."""

    def test_unauthenticated_returns_401(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/countries")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client, test_user: User, valid_jwt_token: str
    ):
        """Test that new user with no visits gets empty response."""
        response = client.get(
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_countries_visited"] == 0
        assert data["countries"] == []

    def test_returns_country_stats(
        self,
        client,
        db_session,
        test_user: User,
        valid_jwt_token: str,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns country statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        response = client.get(
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["total_countries_visited"] == 1
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "USA"
        assert data["countries"][0]["coverage_pct"] == 0.001

    def test_query_params_work(
        self, client, test_user: User, valid_jwt_token: str
    ):
        """Test that query parameters are accepted."""
        response = client.get(
            "/api/v1/stats/countries?sort_by=name&order=asc&limit=10&offset=0",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 200

    def test_invalid_sort_by_returns_422(
        self, client, test_user: User, valid_jwt_token: str
    ):
        """Test that invalid sort_by returns validation error."""
        response = client.get(
            "/api/v1/stats/countries?sort_by=invalid",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 422

    def test_limit_over_100_returns_422(
        self, client, test_user: User, valid_jwt_token: str
    ):
        """Test that limit > 100 returns validation error."""
        response = client.get(
            "/api/v1/stats/countries?limit=101",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestStatsRegionsEndpoint:
    """Test GET /api/v1/stats/regions endpoint."""

    def test_unauthenticated_returns_401(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/regions")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client, test_user: User, valid_jwt_token: str
    ):
        """Test that new user with no visits gets empty response."""
        response = client.get(
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_regions_visited"] == 0
        assert data["regions"] == []

    def test_returns_region_stats(
        self,
        client,
        db_session,
        test_user: User,
        valid_jwt_token: str,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns region statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_state SET land_cells_total_resolution8 = 500 WHERE id = :id
        """), {"id": test_state_california.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        response = client.get(
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["total_regions_visited"] == 1
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"
        assert data["regions"][0]["name"] == "California"
        assert data["regions"][0]["country_code"] == "USA"
        assert data["regions"][0]["coverage_pct"] == 0.002
```

**Step 2: Run the tests**

Run: `cd /Users/ryanpascual/Documents/Trekkr/backend && TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_stats_router.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/tests/test_stats_router.py
git commit -m "$(cat <<'EOF'
test: add stats router integration tests

Test GET /api/v1/stats/countries and GET /api/v1/stats/regions:
- Authentication required (401 without token)
- Empty response for new users
- Returns correct stats with coverage
- Query parameter validation
- Invalid params return 422

EOF
)"
```

---

## Summary

This plan implements two stats endpoints following existing patterns in the codebase:

| Task | Component | Description |
|------|-----------|-------------|
| 1 | Schemas | Pydantic models for request/response |
| 2 | Service | StatsService.get_countries() |
| 3 | Service | StatsService.get_regions() |
| 4 | Router | Stats router with both endpoints |
| 5 | Main | Register router at /api/v1/stats |
| 6 | Tests | StatsService integration tests |
| 7 | Tests | Router integration tests |

**Key patterns followed:**
- Service class with `db` and `user_id` in constructor (like MapService)
- Raw SQL with `text()` for queries
- Query parameters with FastAPI `Query()` annotations
- Integration tests with `@pytest.mark.integration`
- Fixtures from conftest.py
