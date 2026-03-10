"""
Portal dashboard API routes.
Provides authentication and metrics endpoints for the admin portal.
"""

import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.hash import bcrypt

from app.config import settings
from app.db.database import get_session
from app.db.portal_repository import PortalRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "portal" / "templates"

_serializer = URLSafeTimedSerializer(settings.portal_secret_key)
SESSION_COOKIE = "portal_session"
SESSION_MAX_AGE = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _create_session_token(username: str) -> str:
    return _serializer.dumps({"user": username})


def _verify_session_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


def _get_current_user(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = _verify_session_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Session expired")
    return data["user"]


# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def portal_index(request: Request):
    """Redirect to login page."""
    return RedirectResponse(url="/portal/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page. If already authenticated, redirect to dashboard."""
    token = request.cookies.get(SESSION_COOKIE)
    if token and _verify_session_token(token):
        return RedirectResponse(url="/portal/dashboard")
    return HTMLResponse((_TEMPLATES_DIR / "login.html").read_text())


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the dashboard page. Requires authentication."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token or not _verify_session_token(token):
        return RedirectResponse(url="/portal/login")
    return HTMLResponse((_TEMPLATES_DIR / "dashboard.html").read_text())


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(request: Request):
    form = await request.json()
    username = form.get("username", "")
    password = form.get("password", "")

    if not settings.portal_admin_password_hash:
        raise HTTPException(status_code=503, detail="Portal auth not configured")

    if username != settings.portal_admin_username:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.verify(password, settings.portal_admin_password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_session_token(username)
    response = Response(content='{"ok": true}', media_type="application/json")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        max_age=SESSION_MAX_AGE,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout():
    response = Response(content='{"ok": true}', media_type="application/json")
    response.delete_cookie(SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# Metrics API endpoints (protected)
# ---------------------------------------------------------------------------

@router.get("/api/metrics/summary")
async def metrics_summary(
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    repo = PortalRepository(session)
    today = date.today()

    total_users = await repo.get_total_active_users()
    new_users_today = await repo.get_new_users_count("day", today)
    dau = await repo.get_dau(today)
    mau = await repo.get_mau(today.year, today.month)

    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "dau": dau,
        "mau": mau,
    }


@router.get("/api/metrics/new-users")
async def new_users(
    period: str = "day",
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    if period not in ("day", "month", "year"):
        raise HTTPException(status_code=400, detail="period must be day, month, or year")

    repo = PortalRepository(session)
    count = await repo.get_new_users_count(period)
    return {"period": period, "count": count}


@router.get("/api/metrics/growth-trends")
async def growth_trends(
    start: str | None = None,
    end: str | None = None,
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

    repo = PortalRepository(session)
    data = await repo.get_growth_trends(start_date, end_date)
    return {"start": start_date.isoformat(), "end": end_date.isoformat(), "data": data}


@router.get("/api/metrics/activity-trends")
async def activity_trends(
    start: str | None = None,
    end: str | None = None,
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

    repo = PortalRepository(session)
    data = await repo.get_activity_trends(start_date, end_date)
    return {"start": start_date.isoformat(), "end": end_date.isoformat(), "data": data}


@router.get("/api/metrics/segmentation")
async def segmentation(
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    repo = PortalRepository(session)
    data = await repo.get_customer_segmentation()
    return {"data": data}


@router.get("/api/export/users")
async def export_users(
    start: str | None = None,
    end: str | None = None,
    user: str = Depends(_get_current_user),
    session=Depends(get_session),
):
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    repo = PortalRepository(session)
    csv_content = await repo.export_users_csv(start_date, end_date)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )
