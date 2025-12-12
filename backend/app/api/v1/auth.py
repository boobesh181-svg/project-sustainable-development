from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.token import Token
from app.core.security import create_access_token, decode_token
from app.services.auth_service import login as login_service

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
