from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    password: str
    role_id: int


class UserRead(UserBase):
    id: UUID
    is_active: bool
    role_id: int

    class Config:
        from_attributes = True
