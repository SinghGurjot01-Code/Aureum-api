# core/config.py
import os
from typing import Optional

class Settings:
    # App
    app_name: str = "Aureum Music API"
    app_version: str = "2.0.0"
    
    # Redis
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    
    # Cookies (Render only)
    cookies_path: str = os.getenv("COOKIES_PATH", "/etc/secrets/cookies.txt")
    cookies_temp_path: str = "/tmp/cookies.txt"
    
    # Session
    session_ttl: int = 86400  # 24 hours
    
    # Recommendation
    recommendation_limit: int = 20

settings = Settings()