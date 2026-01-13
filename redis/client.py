# redis/client.py
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    log.warning("Redis not available")
    REDIS_AVAILABLE = False
    redis = None

redis_client = None

def get_redis_client() -> Optional[redis.Redis]:
    global redis_client
    
    if redis_client or not REDIS_AVAILABLE:
        return redis_client
    
    try:
        import os
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            redis_client = redis.from_url(redis_url, decode_responses=True)
        else:
            redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", "0")),
                decode_responses=True
            )
        
        log.info("Redis client initialized")
        return redis_client
    except Exception as e:
        log.error(f"Redis failed: {e}")
        return None