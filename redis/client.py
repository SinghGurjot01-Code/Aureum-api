# redis/client.py
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    log.warning("Redis package not available")
    REDIS_AVAILABLE = False
    redis = None

redis_client = None

def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client"""
    global redis_client
    
    if redis_client:
        return redis_client
    
    if not REDIS_AVAILABLE:
        return None
    
    try:
        from core.config import settings
        
        if settings.redis_url:
            redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
        else:
            redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True
            )
        
        log.info("Redis client initialized")
        return redis_client
        
    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        return None