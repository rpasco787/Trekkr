"""Integration tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.device import Device
from models.user import User
from tests.conftest import create_jwt_token


# ============================================================================
# Device Update Endpoint Tests
# ============================================================================

@pytest.mark.integration
class TestDeviceUpdateEndpoint:
    """Test PATCH /api/auth/device endpoint."""

    def test_update_device_metadata(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_device: Device,
    ):
        """Test updating device metadata via PATCH endpoint."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Verify initial device state
        assert test_device.device_name == "Test iPhone"
        assert test_device.platform == "iOS"
        assert test_device.app_version is None

        # Update device metadata
        response = client.patch(
            "/api/auth/device",
            json={
                "device_name": "My New Phone",
                "platform": "android",
                "app_version": "2.1.0",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response contains updated device
        assert data["device_name"] == "My New Phone"
        assert data["platform"] == "android"
        assert data["app_version"] == "2.1.0"

        # Verify database was updated
        db_session.refresh(test_device)
        assert test_device.device_name == "My New Phone"
        assert test_device.platform == "android"
        assert test_device.app_version == "2.1.0"

    def test_update_device_partial_metadata(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        test_device: Device,
    ):
        """Test updating only some device metadata fields."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Update only device_name
        response = client.patch(
            "/api/auth/device",
            json={
                "device_name": "Updated Name",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["device_name"] == "Updated Name"
        assert data["platform"] == "iOS"  # Unchanged

    def test_update_device_unauthenticated_returns_401(
        self,
        client: TestClient,
    ):
        """Test that unauthenticated request returns 401."""
        response = client.patch(
            "/api/auth/device",
            json={"device_name": "New Name"},
        )

        assert response.status_code == 401

    def test_update_device_auto_creates_if_not_exists(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
    ):
        """Test that device is auto-created if user has no device yet."""
        # Verify user has no devices
        devices = db_session.query(Device).filter(
            Device.user_id == test_user.id
        ).all()
        assert len(devices) == 0

        token = create_jwt_token(test_user.id, test_user.username)

        # Update device (should create it)
        response = client.patch(
            "/api/auth/device",
            json={
                "device_name": "First Device",
                "platform": "web",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["device_name"] == "First Device"
        assert data["platform"] == "web"

        # Verify device was created
        devices = db_session.query(Device).filter(
            Device.user_id == test_user.id
        ).all()
        assert len(devices) == 1
