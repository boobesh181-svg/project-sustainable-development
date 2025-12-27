from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


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

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """User response schema for API endpoints."""
    id: str
    email: EmailStr
    full_name: str | None
    is_active: bool
    role: str  # depends on User.role.name
    created_at: str | None = None
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)
