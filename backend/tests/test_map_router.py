"""Integration tests for map endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO


@pytest.mark.integration
class TestMapSummaryEndpoint:
    """Test GET /api/v1/map/summary endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/map/summary")
        assert response.status_code == 401

    def test_authenticated_empty_user_returns_200(
        self, client: TestClient, test_user: User
    ):
        """Test that authenticated user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["countries"] == []
        assert data["regions"] == []

    def test_authenticated_with_visits_returns_data(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits gets their data."""
        # Create visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
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

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "US"
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"
