from sqlalchemy import Column, String, Float, ForeignKey, Boolean, DateTime, Enum, Text, Integer
from sqlalchemy.orm import relationship
import enum
import uuid
from .base import Base

class SensorType(str, enum.Enum):
    ENERGY = "energy"
    WATER_SAVING = "water_saving"
    WASTE = "waste"
    AIR_QUALITY = "air_quality"
    NOISE = "noise"

class SensorReading(Base):
    __tablename__ = "sensor_reading"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sensor_type = Column(Enum(SensorType), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    recorded_at = Column(DateTime, nullable=False, index=True)
    location_lat = Column(Float)
    location_lon = Column(Float)
    sensor_id = Column(String(100))
    metadata = Column(Text)  # JSON string for additional sensor data
    
    # Relationships
    project_id = Column(String(36), ForeignKey('project.id'), nullable=False)
    project = relationship("Project", back_populates="sensor_readings")
    
    def __repr__(self):
        return f"<SensorReading {self.sensor_type}@{self.recorded_at}>"

class AnomalyStatus(str, enum.Enum):
    DETECTED = "detected"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"

class AnomalyType(str, enum.Enum):
    ENERGY_SPIKE = "energy_spike"
    WATER_LEAK = "water_leak"
    WASTE_IRREGULARITY = "waste_irregularity"
    AIR_QUALITY_ISSUE = "air_quality_issue"
    NOISE_POLLUTION = "noise_pollution"
    OTHER = "other"

class AnomalyAlert(Base):
    __tablename__ = "anomaly_alert"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    anomaly_type = Column(Enum(AnomalyType), nullable=False)
    status = Column(Enum(AnomalyStatus), default=AnomalyStatus.DETECTED)
    severity = Column(Integer, default=1)  # 1-5 scale, 5 being most severe
    score = Column(Float, nullable=False)  # Anomaly score from ML model
    description = Column(Text)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36), ForeignKey('user.id'))
    resolution_notes = Column(Text)
    
    # Relationships
    project_id = Column(String(36), ForeignKey('project.id'), nullable=False)
    project = relationship("Project", back_populates="anomaly_alerts")
    resolved_by_user = relationship("User")
    
    def __repr__(self):
        return f"<AnomalyAlert {self.anomaly_type} - {self.status}>"

class MRVReportStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    REJECTED = "rejected"

class MRVReport(Base):
    __tablename__ = "mrv_report"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reporting_period_start = Column(DateTime, nullable=False)
    reporting_period_end = Column(DateTime, nullable=False)
    status = Column(Enum(MRVReportStatus), default=MRVReportStatus.DRAFT)
    total_co2_saved = Column(Float)  # in kg CO2e
    total_energy_saved = Column(Float)  # in kWh
    total_water_saved = Column(Float)  # in liters
    report_data = Column(Text)  # JSON string with full report data
    submitted_at = Column(DateTime)
    verified_at = Column(DateTime)
    verified_by = Column(String(36), ForeignKey('user.id'))
    verification_notes = Column(Text)
    
    # Relationships
    project_id = Column(String(36), ForeignKey('project.id'), nullable=False)
    project = relationship("Project")
    verified_by_user = relationship("User")
    
    def __repr__(self):
        return f"<MRVReport {self.reporting_period_start} to {self.reporting_period_end} - {self.status}>"
