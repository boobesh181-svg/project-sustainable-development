from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoleName(str, PyEnum):
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    CONTRACTOR = "contractor"
    MRV_OFFICER = "mrv_officer"
    SUPPLIER = "supplier"
    CITIZEN = "citizen"


class Role(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[RoleName] = mapped_column(
        SAEnum(RoleName, name="role_name"), unique=True, nullable=False
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="role")
