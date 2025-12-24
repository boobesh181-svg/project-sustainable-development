import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch user by id and eagerly load role.

    Note: accessing relationship attributes (like `user.role.name`) in async
    contexts should avoid lazy-loading.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_uuid)
    )
    return result.scalar_one_or_none()
