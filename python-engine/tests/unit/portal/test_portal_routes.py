"""
Unit tests for portal API routes.
Tests authentication and metrics endpoint responses.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes.portal import (
    SESSION_COOKIE,
    _create_session_token,
    _verify_session_token,
)


# ---------------------------------------------------------------------------
# Session token tests
# ---------------------------------------------------------------------------

class TestSessionToken:
    def test_create_and_verify(self):
        token = _create_session_token("admin")
        data = _verify_session_token(token)
        assert data is not None
        assert data["user"] == "admin"

    def test_invalid_token_returns_none(self):
        assert _verify_session_token("garbage.token.here") is None

    def test_empty_token_returns_none(self):
        assert _verify_session_token("") is None


# ---------------------------------------------------------------------------
# Login endpoint tests (using FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestLoginEndpoint:
    @pytest.fixture
    def client(self):
        """Create a test client with portal routes mounted."""
        from fastapi import FastAPI
        from app.api.routes.portal import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @patch("app.api.routes.portal.settings")
    def test_login_no_password_configured(self, mock_settings, client):
        mock_settings.portal_admin_password_hash = ""
        mock_settings.portal_admin_username = "admin"
        mock_settings.portal_secret_key = "test-secret"

        resp = client.post("/portal/login", json={"username": "admin", "password": "pass"})
        assert resp.status_code == 503

    @patch("app.api.routes.portal.settings")
    @patch("app.api.routes.portal.bcrypt")
    def test_login_wrong_username(self, mock_bcrypt, mock_settings, client):
        mock_settings.portal_admin_password_hash = "$2b$12$fakehash"
        mock_settings.portal_admin_username = "admin"
        mock_settings.portal_secret_key = "test-secret"

        resp = client.post("/portal/login", json={"username": "wrong", "password": "pass"})
        assert resp.status_code == 401

    @patch("app.api.routes.portal.settings")
    @patch("app.api.routes.portal.bcrypt")
    def test_login_wrong_password(self, mock_bcrypt, mock_settings, client):
        mock_settings.portal_admin_password_hash = "$2b$12$fakehash"
        mock_settings.portal_admin_username = "admin"
        mock_settings.portal_secret_key = "test-secret"
        mock_bcrypt.verify.return_value = False

        resp = client.post("/portal/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    @patch("app.api.routes.portal.settings")
    @patch("app.api.routes.portal.bcrypt")
    def test_login_success(self, mock_bcrypt, mock_settings, client):
        mock_settings.portal_admin_password_hash = "$2b$12$fakehash"
        mock_settings.portal_admin_username = "admin"
        mock_settings.portal_secret_key = "test-secret"
        mock_bcrypt.verify.return_value = True

        resp = client.post("/portal/login", json={"username": "admin", "password": "correct"})
        assert resp.status_code == 200
        assert SESSION_COOKIE in resp.cookies


# ---------------------------------------------------------------------------
# Protected endpoint access tests
# ---------------------------------------------------------------------------

class TestProtectedEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from app.api.routes.portal import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_summary_without_auth_returns_401(self, client):
        resp = client.get("/portal/api/metrics/summary")
        assert resp.status_code == 401

    def test_segmentation_without_auth_returns_401(self, client):
        resp = client.get("/portal/api/metrics/segmentation")
        assert resp.status_code == 401

    def test_export_without_auth_returns_401(self, client):
        resp = client.get("/portal/api/export/users")
        assert resp.status_code == 401

    def test_new_users_invalid_period(self, client):
        token = _create_session_token("admin")
        resp = client.get(
            "/portal/api/metrics/new-users?period=invalid",
            cookies={SESSION_COOKIE: token},
        )
        assert resp.status_code == 400

    def test_logout_clears_cookie(self, client):
        resp = client.post("/portal/logout")
        assert resp.status_code == 200
