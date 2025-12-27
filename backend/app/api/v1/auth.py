from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.token import Token
from app.schemas.user import UserResponse
from app.core.config import settings
from app.core.security import create_access_token, decode_token
from app.services.auth_service import login as login_service
from app.models.user import User

router = APIRouter()


def _is_secure_cookie() -> bool:
    return settings.ENV.lower() in {"production", "prod"}


@router.post("/login", response_model=Token)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Token:
    token = await login_service(db, payload)

    # Set HttpOnly cookies for browser clients (still returns token body for API clients).
    secure = _is_secure_cookie()
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=token.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return token


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, response: Response) -> Token:
    data = decode_token(payload.refresh_token, token_type="refresh")
    sub = data.get("sub")
    new_access = create_access_token(str(sub))
    # keep same refresh for simplicity here
    token = Token(access_token=new_access, refresh_token=payload.refresh_token)

    secure = _is_secure_cookie()
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return token


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current user information."""
    # Pydantic schema expects simple JSON-friendly primitives.
    role = current_user.role.name.value if getattr(current_user, "role", None) else "unknown"
    created_at = current_user.created_at.isoformat() if getattr(current_user, "created_at", None) else None
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        role=role,
        created_at=created_at,
        updated_at=None,
    )
