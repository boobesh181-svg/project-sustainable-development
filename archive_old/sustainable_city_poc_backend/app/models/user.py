from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .base import Base

# Association table for many-to-many relationship between User and Role
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', String(36), ForeignKey('user.id')),
    Column('role_id', String(36), ForeignKey('role.id'))
)

class User(Base):
    __tablename__ = "user"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    last_login = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    projects = relationship("Project", back_populates="owner")
    
    def __repr__(self):
        return f"<User {self.email}>"

class Role(Base):
    __tablename__ = "role"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(255))
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    def __repr__(self):
        return f"<Role {self.name}>"
