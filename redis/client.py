# redis/client.py
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Default to simple client
USE_SIMPLE_CLIENT = True
redis_client = None

def get_redis_client():
    """Get Redis client with automatic fallback"""
    global redis_client, USE_SIMPLE_CLIENT
    
    if redis_client:
        return redis_client
    
    # First try to use real Redis if not forced to use simple client
    if not USE_SIMPLE_CLIENT:
        try:
            import redis.asyncio as redis_async
            from core.config import settings
            
            if settings.redis_url:
                redis_client = redis_async.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            else:
                redis_client = redis_async.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            
            log.info("Real Redis client initialized")
            return redis_client
        except ImportError:
            log.warning("Redis package not installed, falling back to simple client")
            USE_SIMPLE_CLIENT = True
        except Exception as e:
            log.warning(f"Redis connection failed: {e}, falling back to simple client")
            USE_SIMPLE_CLIENT = True
    
    # Fall back to simple client
    try:
        from .simple_client import get_simple_redis_client
        redis_client = get_simple_redis_client()
        log.info("Using simple Redis fallback client")
        return redis_client
    except ImportError as e:
        log.error(f"Simple Redis client also failed: {e}")
        # Create a dummy client that does nothing
        class DummyClient:
            async def get(self, *args, **kwargs): return None
            async def set(self, *args, **kwargs): return False
            async def delete(self, *args, **kwargs): return False
            async def ping(self): return False
            async def close(self): pass
            async def lpush(self, *args, **kwargs): return 0
            async def lrange(self, *args, **kwargs): return []
            async def ltrim(self, *args, **kwargs): return False
            async def expire(self, *args, **kwargs): return False
            async def exists(self, *args, **kwargs): return 0
        
        redis_client = DummyClient()
        return redis_client