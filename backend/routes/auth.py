"""Demo authentication endpoints.

The competition dashboard uses a lightweight mock auth: credentials are checked
against ``config.Settings`` (env-overridable) and a fixed session token is
returned. The user profile is demo data served for the dashboard — nothing is
stored on the server.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.schemas import LoginIn, LoginOut, UserOut
from config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_settings()


def _user_out() -> UserOut:
    """Build the demo profile payload (dummy data, env-overridable)."""
    return UserOut(
        name=settings.demo_user_name,
        role=settings.demo_user_role,
        email=settings.demo_username,
        job_title=settings.demo_job_title,
        department=settings.demo_department,
        employee_id=settings.demo_employee_id,
        phone=settings.demo_phone,
        location=settings.demo_location,
        joined=settings.demo_joined,
        timezone=settings.demo_timezone,
        last_login=settings.demo_last_login,
    )


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn) -> LoginOut:
    if payload.username != settings.demo_username or payload.password != settings.demo_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return LoginOut(token=settings.session_token, user=_user_out())


@router.get("/session", response_model=UserOut)
def session(authorization: str | None = Header(default=None)) -> UserOut:
    token = _extract_token(authorization)
    if token != settings.session_token:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return _user_out()


@router.post("/logout")
def logout() -> dict[str, str]:
    # Stateless demo auth: the client clears its stored token.
    return {"status": "ok"}


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" else authorization
