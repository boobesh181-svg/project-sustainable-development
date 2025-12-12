import uuid

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Supplier(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    partnership_discount: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    total_value_supplied: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
