"""Integration tests for stats endpoints."""

from datetime import datetime, timedelta


def test_overview_integration_new_user_journey(client, db_session):
    """Test complete user journey: register -> first visit -> check overview."""
    # Register new user
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "TestPass123",
        },
    )
    assert register_response.status_code == 201

    # Login to get token (using form data as expected by OAuth2)
    login_response = client.post(
        "/api/auth/login",
        data={"username": "newuser@test.com", "password": "TestPass123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check overview (should have zeros)
    overview_response = client.get("/api/v1/stats/overview", headers=headers)
    assert overview_response.status_code == 200
    data = overview_response.json()

    assert data["stats"]["countries_visited"] == 0
    assert data["stats"]["cells_visited_res8"] == 0
    assert data["recent_countries"] == []
