# models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Session models
class SessionStartRequest(BaseModel):
    user_id: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    location: Optional[str] = None

class SessionEventRequest(BaseModel):
    session_id: str
    event_type: str = Field(..., description="play, pause, skip, like, dislike")
    video_id: Optional[str] = None
    timestamp: Optional[str] = None
    user_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

# Track model (preserved from original)
class Track(BaseModel):
    videoId: str
    title: str
    artists: str
    thumbnail: str
    duration: str
    duration_seconds: int

# Recommendation models
class RecommendationRequest(BaseModel):
    current_track: Optional[Dict[str, Any]] = None
    recent_activity: Optional[List[Dict[str, Any]]] = None
    user_id: Optional[str] = None
    taste_profile: Optional[Dict[str, Any]] = None
    limit: int = 20

class RecommendationResponse(BaseModel):
    tracks: List[Dict[str, Any]]
    labels: List[str]
    context: Dict[str, Any]
    generated_at: str

# Cache manifest models
class CacheManifestResponse(BaseModel):
    must_cache: List[Dict[str, Any]]
    likely_next: List[Dict[str, Any]]
    expires_at: int

# Health check model
class HealthResponse(BaseModel):
    status: str
    ytmusic_ready: bool
    redis_ready: bool
    version: str