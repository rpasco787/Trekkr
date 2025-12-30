"""Tests for AchievementService.

Tests achievement evaluation logic and unlock functionality.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.achievements import Achievement, UserAchievement
from models.user import User
from services.achievement_service import AchievementService
from tests.fixtures.test_data import SAN_FRANCISCO, SYDNEY


@pytest.fixture
def seed_achievements(db_session: Session) -> list[Achievement]:
    """Seed test achievements into the database."""
    achievements_data = [
        {"code": "first_steps", "name": "First Steps", "description": "Visit your first location",
         "criteria_json": {"type": "cells_total", "threshold": 1}},
        {"code": "explorer", "name": "Explorer", "description": "Visit 100 unique cells",
         "criteria_json": {"type": "cells_total", "threshold": 100}},
        {"code": "globetrotter", "name": "Globetrotter", "description": "Visit 10 countries",
         "criteria_json": {"type": "countries", "threshold": 10}},
        {"code": "continental", "name": "Continental", "description": "Visit 3 continents",
         "criteria_json": {"type": "continents", "threshold": 3}},
        {"code": "hemisphere_hopper", "name": "Hemisphere Hopper", "description": "Visit both hemispheres",
         "criteria_json": {"type": "hemispheres", "count": 2}},
        {"code": "state_hopper", "name": "State Hopper", "description": "Visit 5 regions in one country",
         "criteria_json": {"type": "regions_in_country", "threshold": 5}},
        {"code": "regional_master", "name": "Regional Master", "description": "Visit 50 regions",
         "criteria_json": {"type": "regions", "threshold": 50}},
        {"code": "country_explorer", "name": "Country Explorer", "description": "10% coverage of any country",
         "criteria_json": {"type": "country_coverage_pct", "threshold": 0.10}},
        {"code": "region_explorer", "name": "Region Explorer", "description": "25% coverage of any region",
         "criteria_json": {"type": "region_coverage_pct", "threshold": 0.25}},
        {"code": "frequent_traveler", "name": "Frequent Traveler", "description": "Visit on 30 unique days",
         "criteria_json": {"type": "unique_days", "threshold": 30}},
    ]

    achievements = []
    for data in achievements_data:
        achievement = Achievement(**data)
        db_session.add(achievement)
        achievements.append(achievement)

    db_session.commit()
    for a in achievements:
        db_session.refresh(a)

    return achievements


@pytest.fixture
def test_country_with_continent(db_session: Session):
    """Create USA with continent for testing."""
    db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, continent, geom, land_cells_total_resolution8, created_at, updated_at)
        VALUES (
            'United States', 'US', 'USA', 'North America',
            ST_GeomFromText('POLYGON((-125 30, -125 50, -115 50, -115 30, -125 30))', 4326),
            1000,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """))
    db_session.commit()
    result = db_session.execute(text("SELECT id FROM regions_country WHERE iso2 = 'US'")).fetchone()
    return result.id


@pytest.fixture
def test_country_australia(db_session: Session):
    """Create Australia (southern hemisphere) for testing."""
    db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, continent, geom, land_cells_total_resolution8, created_at, updated_at)
        VALUES (
            'Australia', 'AU', 'AUS', 'Oceania',
            ST_GeomFromText('POLYGON((140 -40, 140 -10, 155 -10, 155 -40, 140 -40))', 4326),
            5000,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """))
    db_session.commit()
    result = db_session.execute(text("SELECT id FROM regions_country WHERE iso2 = 'AU'")).fetchone()
    return result.id


class TestCheckAndUnlock:
    """Test the check_and_unlock method."""

    def test_unlocks_first_steps_on_first_cell(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """First cell visit should unlock 'first_steps' achievement."""
        # Create one cell visit for user
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        assert len(newly_unlocked) >= 1
        codes = [a.code for a in newly_unlocked]
        assert "first_steps" in codes

    def test_returns_only_newly_unlocked(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Already unlocked achievements should not be returned again."""
        # Create cell visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)

        # First call unlocks first_steps
        first_unlocked = service.check_and_unlock()
        assert any(a.code == "first_steps" for a in first_unlocked)

        # Second call should not return first_steps again
        second_unlocked = service.check_and_unlock()
        assert not any(a.code == "first_steps" for a in second_unlocked)

    def test_no_unlock_when_threshold_not_met(
        self, db_session: Session, test_user: User, seed_achievements: list
    ):
        """No achievements should unlock when user has no cells."""
        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        assert len(newly_unlocked) == 0


class TestEvaluateCriteria:
    """Test individual criteria evaluation."""

    def test_cells_total_criteria(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Test cells_total criteria type."""
        # Add exactly 100 cells
        for i in range(100):
            h3_index = f"88283082{i:07d}"  # Generate unique h3 indexes
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
                VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
                ON CONFLICT (h3_index) DO NOTHING
            """), {"h3": h3_index, "country_id": test_country_with_continent})

            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
            """), {"user_id": test_user.id, "h3": h3_index})

        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        codes = [a.code for a in newly_unlocked]
        assert "first_steps" in codes  # threshold: 1
        assert "explorer" in codes     # threshold: 100

    def test_hemispheres_criteria(
        self, db_session: Session, test_user: User, seed_achievements: list,
        test_country_with_continent: int, test_country_australia: int
    ):
        """Test hemispheres criteria (N/S detection based on latitude)."""
        # Add cell in northern hemisphere (USA)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_with_continent,
            "lat": SAN_FRANCISCO["latitude"],
            "lon": SAN_FRANCISCO["longitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})

        # Add cell in southern hemisphere (Australia)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3": SYDNEY["h3_res8"],
            "country_id": test_country_australia,
            "lat": SYDNEY["latitude"],
            "lon": SYDNEY["longitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SYDNEY["h3_res8"]})

        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        codes = [a.code for a in newly_unlocked]
        assert "hemisphere_hopper" in codes


class TestGetAllWithStatus:
    """Test the get_all_with_status method."""

    def test_returns_all_achievements_with_unlock_status(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Should return all achievements with correct unlock status."""
        # Create one cell to unlock first_steps
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        service.check_and_unlock()  # Unlock first_steps

        all_achievements = service.get_all_with_status()

        assert len(all_achievements) == 10  # All seeded achievements

        first_steps = next(a for a in all_achievements if a["code"] == "first_steps")
        assert first_steps["unlocked"] is True
        assert first_steps["unlocked_at"] is not None

        explorer = next(a for a in all_achievements if a["code"] == "explorer")
        assert explorer["unlocked"] is False
        assert explorer["unlocked_at"] is None

    def test_returns_empty_for_new_user(
        self, db_session: Session, test_user: User, seed_achievements: list
    ):
        """New user should have all achievements locked."""
        service = AchievementService(db_session, test_user.id)
        all_achievements = service.get_all_with_status()

        assert all(a["unlocked"] is False for a in all_achievements)
        assert all(a["unlocked_at"] is None for a in all_achievements)
