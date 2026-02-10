from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class UserRole(str, PyEnum):
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    CONTRACTOR = "contractor"
    MRV_OFFICER = "mrv_officer"
    SUPPLIER = "supplier"
    CITIZEN = "citizen"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CITIZEN)
    is_active = Column(Boolean(), default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    projects = relationship("Project", back_populates="owner")
    material_tokens = relationship("MaterialToken", back_populates="issuer")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
