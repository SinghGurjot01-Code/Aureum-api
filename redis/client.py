# redis/client.py - Updated version
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Try to import Redis with multiple fallbacks
try:
    # Python 3.13+ compatibility
    import redis.asyncio as redis
    log.info("Using redis.asyncio")
except ImportError:
    try:
        # Older redis versions
        import redis
        # Check if it's async-capable
        if hasattr(redis, 'asyncio'):
            import redis.asyncio as redis
            log.info("Using redis.asyncio from main package")
        else:
            # Use sync Redis with async wrapper
            log.info("Using sync Redis with wrapper")
            from .sync_wrapper import AsyncRedisWrapper
            redis = AsyncRedisWrapper
    except ImportError:
        log.error("Redis package not available")
        redis = None

# Only define functions if redis is available
if redis is not None:
    redis_client: Optional[redis.Redis] = None

    def get_redis_client() -> Optional[redis.Redis]:
        """Get Redis connection with fallback handling"""
        global redis_client
        
        if redis_client:
            return redis_client
        
        try:
            from core.config import settings
            
            if settings.redis_url:
                redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            log.info("Redis client initialized")
            return redis_client
            
        except Exception as e:
            log.error(f"Redis connection failed: {e}")
            redis_client = None
            return None
else:
    # Redis not available at all
    def get_redis_client():
        log.warning("Redis package not installed")
        return None