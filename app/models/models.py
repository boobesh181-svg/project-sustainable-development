from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Enum, JSON
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    admin = "admin"
    project_manager = "project_manager"
    contractor = "contractor"
    mrv_officer = "mrv_officer"
    supplier = "supplier"
    citizen = "citizen"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.citizen)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    budget_usd = Column(Float, default=0.0)
    status = Column(String, default="draft")

class MaterialToken(Base):
    __tablename__ = "material_tokens"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    material_type = Column(String, index=True)
    qty = Column(Float, default=0.0)   # tonnes
    unit_price = Column(Float, nullable=True)
    supplier = Column(String, nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow)
    redeemed = Column(Boolean, default=False)
    redemption_lat = Column(Float, nullable=True)
    redemption_lon = Column(Float, nullable=True)
    recycled = Column(Boolean, default=False)

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    sensor_type = Column(String, index=True)  # energy, water_saving
    value = Column(Float)
    unit = Column(String)
    ts = Column(DateTime, default=datetime.utcnow)

class MRVReport(Base):
    __tablename__ = "mrv_reports"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    parameter = Column(String)
    value = Column(String)
    certificate_path = Column(String, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")

class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"
    id = Column(Integer, primary_key=True)
    event_id = Column(String, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    entity_type = Column(String, nullable=True)
    score = Column(Float, default=0.0)
    rule_score = Column(Float, default=0.0)
    ml_score = Column(Float, default=0.0)
    flagged = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Whistleblower(Base):
    __tablename__ = "whistleblowers"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    message = Column(String)
    evidence_path = Column(String, nullable=True)
    status = Column(String, default="new")
    priority = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
