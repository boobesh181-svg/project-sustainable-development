from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.user import UserRead
from app.models.user import User

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
