from sqlalchemy import Column, String, Float, Numeric, Enum, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
import enum
import uuid
from .base import Base

class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"

class Project(Base):
    __tablename__ = "project"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    budget_usd = Column(Numeric(12, 2), default=0.0)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.IN_PROGRESS)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Relationships
    owner_id = Column(String(36), ForeignKey('user.id'))
    owner = relationship("User", back_populates="projects")
    material_tokens = relationship("MaterialToken", back_populates="project")
    sensor_readings = relationship("SensorReading", back_populates="project")
    anomaly_alerts = relationship("AnomalyAlert", back_populates="project")
    
    def __repr__(self):
        return f"<Project {self.name}>"

class MaterialToken(Base):
    __tablename__ = "material_token"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_type = Column(String(100), nullable=False)
    qty = Column(Numeric(10, 2), nullable=False)  # in tonnes
    unit_price = Column(Numeric(10, 2), nullable=False)
    supplier = Column(String(255))
    issued_at = Column(DateTime, nullable=False)
    redeemed = Column(Boolean, default=False)
    redemption_date = Column(DateTime)
    redemption_lat = Column(Float)
    redemption_lon = Column(Float)
    recycled = Column(Boolean, default=False)
    evidence_url = Column(String(500))  # URL to uploaded evidence
    
    # Relationships
    project_id = Column(String(36), ForeignKey('project.id'), nullable=False)
    project = relationship("Project", back_populates="material_tokens")
    
    def __repr__(self):
        return f"<MaterialToken {self.id} - {self.material_type}>"
