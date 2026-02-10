from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import User, RefreshToken, RoleEnum
from app.schemas.schemas import Token, UserCreate, UserOut
from app.utils.security import hash_password, verify_password, create_access_token, create_refresh_token
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(User).where(User.email == payload.email))
    existing = q.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Email exists")
    user = User(
        email=payload.email, 
        hashed_password=hash_password(payload.password), 
        full_name=payload.full_name, 
        role=payload.role or RoleEnum.citizen
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login(form_data: UserCreate, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(User).where(User.email == form_data.email))
    user = q.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rtoken = RefreshToken(user_id=user.id, token=refresh, expires_at=expires)
    db.add(rtoken)
    await db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: dict, db: AsyncSession = Depends(get_db)):
    token_str = refresh_token.get("refresh_token")
    if not token_str:
        raise HTTPException(status_code=400, detail="Missing token")
    q = await db.execute(select(RefreshToken).where(RefreshToken.token == token_str))
    stored = q.scalars().first()
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        payload = jwt.decode(token_str, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    access = create_access_token({"sub": str(user_id)})
    refresh = create_refresh_token({"sub": str(user_id)})
    stored.token = refresh
    await db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}
