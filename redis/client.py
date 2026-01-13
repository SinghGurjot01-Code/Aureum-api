# redis/client.py
import logging
import redis.asyncio as redis
from typing import Optional
from core.config import settings

log = logging.getLogger(__name__)

# Global Redis client
redis_client: Optional[redis.Redis] = None

def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis connection with fallback handling"""
    global redis_client
    
    if redis_client:
        return redis_client
    
    try:
        if settings.redis_url:
            # Use Redis URL if provided
            redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        else:
            # Use host/port configuration
            redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        
        log.info(f"Redis connected to {settings.redis_host}:{settings.redis_port}")
        return redis_client
        
    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        redis_client = None
        return None

async def is_redis_available() -> bool:
    """Check if Redis is available"""
    client = get_redis_client()
    if not client:
        return False
    
    try:
        await client.ping()
        return True
    except Exception as e:
        log.warning(f"Redis ping failed: {e}")
        return False

async def safe_redis_get(key: str) -> Optional[str]:
    """Safe Redis get with fallback"""
    try:
        if await is_redis_available():
            return await redis_client.get(key)
    except Exception as e:
        log.debug(f"Redis get failed for key {key}: {e}")
    return None

async def safe_redis_set(key: str, value: str, ttl: int = None) -> bool:
    """Safe Redis set with fallback"""
    try:
        if await is_redis_available():
            await redis_client.set(key, value, ex=ttl)
            return True
    except Exception as e:
        log.debug(f"Redis set failed for key {key}: {e}")
    return False

async def safe_redis_delete(key: str) -> bool:
    """Safe Redis delete with fallback"""
    try:
        if await is_redis_available():
            await redis_client.delete(key)
            return True
    except Exception as e:
        log.debug(f"Redis delete failed for key {key}: {e}")
    return False