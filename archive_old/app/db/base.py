from datetime import datetime
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.config import settings


@as_declarative()
class Base:
    id: Any
    __name__: str
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def to_dict(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UUIDMixin:
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
