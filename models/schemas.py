# models/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class Track(BaseModel):
    videoId: str
    title: str
    artists: str
    thumbnail: str
    duration: str
    duration_seconds: int

class RecommendationResponse(BaseModel):
    tracks: List[Dict[str, Any]]
    context: Dict[str, Any]
    generated_at: str

class CacheManifestResponse(BaseModel):
    must_cache: List[Dict[str, Any]]
    likely_next: List[Dict[str, Any]]
    expires_at: int