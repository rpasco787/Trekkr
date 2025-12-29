"""Integration tests for MapService."""

import pytest
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from services.map_service import MapService
from tests.fixtures.test_data import SAN_FRANCISCO, TOKYO, LOS_ANGELES


@pytest.mark.integration
class TestMapServiceSummary:
    """Test MapService.get_summary() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns empty arrays."""
        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert result["countries"] == []
        assert result["regions"] == []

    def test_user_with_one_visit_returns_country_and_region(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with one visit returns that country and region."""
        # Create a cell visit for the user
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
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
        })
        db_session.commit()

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert len(result["countries"]) == 1
        assert result["countries"][0]["code"] == "US"
        assert result["countries"][0]["name"] == "United States"

        assert len(result["regions"]) == 1
        assert result["regions"][0]["code"] == "US-CA"
        assert result["regions"][0]["name"] == "California"

    def test_multiple_visits_same_country_returns_one_country(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that multiple visits to same country return one entry."""
        # Create two cell visits in the same country
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

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        # Should have only one country entry (deduplicated)
        assert len(result["countries"]) == 1
        assert result["countries"][0]["code"] == "US"

    def test_visits_in_multiple_countries(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
        test_country_japan: CountryRegion,
    ):
        """Test visits in multiple countries returns all."""
        # Visit in USA
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

        # Visit in Japan
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

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert len(result["countries"]) == 2
        country_codes = {c["code"] for c in result["countries"]}
        assert country_codes == {"US", "JP"}


@pytest.mark.integration
class TestMapServiceCells:
    """Test MapService.get_cells_in_viewport() method."""

    def test_no_cells_in_viewport_returns_empty(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that empty viewport returns empty arrays."""
        # Create cell in San Francisco
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

        service = MapService(db_session, test_user.id)

        # Query viewport in Tokyo (no cells there)
        result = service.get_cells_in_viewport(
            min_lng=139.0, min_lat=35.0, max_lng=140.0, max_lat=36.0
        )

        assert result["res6"] == []
        assert result["res8"] == []

    def test_cells_in_viewport_returned(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that cells within viewport are returned."""
        # Create res-6 and res-8 cells in San Francisco
        for h3_index, res in [
            (SAN_FRANCISCO["h3_res6"], 6),
            (SAN_FRANCISCO["h3_res8"], 8),
        ]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
                VALUES (:h3_index, :res, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": h3_index,
                "res": res,
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": SAN_FRANCISCO["longitude"],
                "lat": SAN_FRANCISCO["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, :res, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {"user_id": test_user.id, "h3_index": h3_index, "res": res})

        db_session.commit()

        service = MapService(db_session, test_user.id)

        # Query viewport around San Francisco
        result = service.get_cells_in_viewport(
            min_lng=-123.0, min_lat=37.0, max_lng=-122.0, max_lat=38.0
        )

        assert len(result["res6"]) == 1
        assert result["res6"][0] == SAN_FRANCISCO["h3_res6"]
        assert len(result["res8"]) == 1
        assert result["res8"][0] == SAN_FRANCISCO["h3_res8"]

    def test_only_user_cells_returned(
        self,
        db_session,
        test_user: User,
        test_user2: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that only the requesting user's cells are returned."""
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

        # Query as user 1 with viewport covering both SF and LA
        service = MapService(db_session, test_user.id)
        result = service.get_cells_in_viewport(
            min_lng=-125.0, min_lat=32.0, max_lng=-115.0, max_lat=40.0
        )

        # Should only see user 1's SF cell, not user 2's LA cell
        assert len(result["res8"]) == 1
        assert result["res8"][0] == SAN_FRANCISCO["h3_res8"]

    def test_user_with_no_visits_returns_empty(self, db_session, test_user: User):
        """Test that user with no visits returns empty arrays for any viewport."""
        service = MapService(db_session, test_user.id)

        result = service.get_cells_in_viewport(
            min_lng=-180.0, min_lat=-90.0, max_lng=180.0, max_lat=90.0
        )

        assert result["res6"] == []
        assert result["res8"] == []
