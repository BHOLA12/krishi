from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class LocationInput(BaseModel):
    latitude: Optional[float] = Field(None, description="GPS Latitude coordinate")
    longitude: Optional[float] = Field(None, description="GPS Longitude coordinate")
    cell_tower_id: Optional[str] = Field(None, description="Telecom Cell Tower ID metadata")
    ip_address: Optional[str] = Field(None, description="Client IP address fallback")

class SMSQueryRequest(BaseModel):
    query_text: str = Field(..., description="Raw SMS text message from the farmer")
    sender_phone: str = Field(..., description="Farmer's phone number")
    location: Optional[LocationInput] = None

class VoiceQueryRequest(BaseModel):
    # For voice, audio is uploaded as a form file, metadata is passed separately
    sender_phone: str = Field(..., description="Farmer's phone number")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cell_tower_id: Optional[str] = None
    ip_address: Optional[str] = None

class CoreAIResponseSchema(BaseModel):
    intent: str = Field(..., description="Category (Agriculture / Horticulture / Animal_Husbandry / Fish_Farming / Poultry / Govt_Schemes / Weather / Market_Prices)")
    detected_disease_or_need: str = Field(..., description="Detected issue name")
    voice_response: str = Field(..., description="Short IVR-ready conversational response in rural dialect")
    sms_payload: str = Field(..., description="Compact SMS advisory")

class QueryResponse(BaseModel):
    query_id: UUID
    query_type: str
    detected_language: Optional[str]
    detected_dialect: Optional[str]
    intent: Optional[str]
    detected_disease_or_need: Optional[str]
    voice_response: str
    voice_response_audio_url: Optional[str] = None
    sms_payload: str
    
    # Enriched weather & location
    resolved_location: Dict[str, Any]
    enriched_weather: Dict[str, Any]
    
    created_at: datetime

    class Config:
        from_attributes = True

class SystemHealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    services: Dict[str, str]


class AgentCreate(BaseModel):
    name: str = Field(..., description="Name of the agricultural agent")
    phone: str = Field(..., description="Contact phone number of the agent")
    specialization: str = Field(..., description="Specialization (e.g. Soil Health, Crop Protection, Poultry)")
    state: str = Field(..., description="State of operation")
    district: str = Field(..., description="District of operation")
    is_available: Optional[bool] = Field(True, description="Availability status of the agent")


class AgentOut(BaseModel):
    id: UUID
    name: str
    phone: str
    specialization: str
    state: str
    district: str
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    farmer_phone: str = Field(..., description="Contact phone number of the booking farmer")
    crop_type: Optional[str] = Field(None, description="Crop type related to the booking inquiry")
    problem_description: Optional[str] = Field(None, description="Detailed description of the problem/requirements")
    scheduled_date: datetime = Field(..., description="Date and time scheduled for the agent visit")


class BookingOut(BaseModel):
    id: UUID
    agent_id: UUID
    farmer_phone: str
    crop_type: Optional[str]
    problem_description: Optional[str]
    status: str
    scheduled_date: datetime
    created_at: datetime
    agent: Optional[AgentOut] = None

    class Config:
        from_attributes = True
