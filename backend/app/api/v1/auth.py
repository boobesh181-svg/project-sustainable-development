from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.token import Token
from app.schemas.user import UserResponse
from app.core.security import create_access_token, decode_token
from app.services.auth_service import login as login_service
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    return await login_service(db, payload)


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest) -> Token:
    data = decode_token(payload.refresh_token, token_type="refresh")
    sub = data.get("sub")
    new_access = create_access_token(str(sub))
    # keep same refresh for simplicity here
    return Token(access_token=new_access, refresh_token=payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current user information."""
    return UserResponse.model_validate(current_user)
