import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Uuid, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base

class FarmerQuery(Base):
    __tablename__ = "farmer_queries"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    query_type = Column(String(10), nullable=False)  # "voice" or "sms"
    audio_path = Column(String(500), nullable=True)   # Local storage path of audio query
    raw_text = Column(Text, nullable=True)           # Original text query (for SMS)
    transcribed_text = Column(Text, nullable=True)   # Text transcribed from audio
    normalized_text = Column(Text, nullable=True)    # Query translated/normalized to standard Hindi/English
    detected_language = Column(String(50), nullable=True)
    detected_dialect = Column(String(50), nullable=True)
    intent = Column(String(100), nullable=True)
    detected_disease_or_need = Column(String(255), nullable=True)
    
    # Location Metadata
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    block = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)

    # Weather/Environment Enrichment
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    soil_type = Column(String(100), nullable=True)
    active_season = Column(String(50), nullable=True)
    mandi_price_info = Column(JSON, nullable=True)

    # Response Data
    voice_response_text = Column(Text, nullable=True)
    voice_response_audio_path = Column(String(500), nullable=True)
    sms_payload = Column(Text, nullable=True)
    raw_ai_response = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    location_audits = relationship("LocationAudit", back_populates="farmer_query", cascade="all, delete-orphan")


class LocationAudit(Base):
    __tablename__ = "location_audits"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    query_id = Column(Uuid, ForeignKey("farmer_queries.id"), nullable=False)
    cell_tower_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    resolved_state = Column(String(100), nullable=True)
    resolved_district = Column(String(100), nullable=True)
    resolved_block = Column(String(100), nullable=True)
    resolved_village = Column(String(100), nullable=True)
    lookup_status = Column(String(50), nullable=False)  # "success", "partial_fallback", "full_fallback"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    farmer_query = relationship("FarmerQuery", back_populates="location_audits")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    log_level = Column(String(20), nullable=False)
    module = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    exception_trace = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AgriculturalAgent(Base):
    __tablename__ = "agricultural_agents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    specialization = Column(String(100), nullable=False)  # e.g., "Soil Health", "Crop Protection"
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    bookings = relationship("AgentBooking", back_populates="agent", cascade="all, delete-orphan")


class AgentBooking(Base):
    __tablename__ = "agent_bookings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id = Column(Uuid, ForeignKey("agricultural_agents.id"), nullable=False)
    farmer_phone = Column(String(20), nullable=False)
    crop_type = Column(String(100), nullable=True)
    problem_description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # "pending", "confirmed", "completed", "cancelled"
    scheduled_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    agent = relationship("AgriculturalAgent", back_populates="bookings")
