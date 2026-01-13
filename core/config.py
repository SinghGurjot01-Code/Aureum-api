# core/config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    app_name: str = "Aureum Music API"
    app_version: str = "2.0.0"
    
    # Redis
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    
    # Session
    session_ttl: int = 86400  # 24 hours
    event_ttl: int = 604800   # 7 days
    
    # Cookies (existing functionality)
    cookies_readonly_path: str = "/etc/secrets/cookies.txt"
    cookies_writable_path: str = "/tmp/cookies.txt"
    cookies_env_var: str = "YT_COOKIES"
    
    # Recommendation
    recommendation_limit: int = 20
    recent_activity_window: int = 50  # tracks
    similar_artist_limit: int = 5
    
    # Cache prediction
    cache_prediction_hours: int = 24
    must_cache_size: int = 10
    likely_next_size: int = 20
    
    # Search enhancement
    fuzzy_search_threshold: float = 0.6
    fallback_expansion_limit: int = 5
    
    class Config:
        env_file = ".env"

settings = Settings()