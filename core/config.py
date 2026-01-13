# core/config.py
import os

class Settings:
    app_name = "Aureum Music API"
    version = "2.0.0"
    
    # Redis
    redis_url = os.getenv("REDIS_URL")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD")
    redis_db = int(os.getenv("REDIS_DB", "0"))
    
    # Session
    session_ttl = 86400  # 24 hours
    event_ttl = 604800   # 7 days

settings = Settings()