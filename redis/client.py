# redis/client.py
import logging
from typing import Optional
import asyncio
from core.config import settings

log = logging.getLogger(__name__)

# Try different Redis imports for compatibility
try:
    # Try newer redis.asyncio
    import redis.asyncio as redis
    log.info("Using redis.asyncio")
except ImportError:
    try:
        # Try older aioredis
        import aioredis
        log.info("Using aioredis")
        
        # Create compatibility wrapper
        class RedisWrapper:
            def __init__(self):
                self.client = None
            
            async def from_url(self, url, **kwargs):
                self.client = await aioredis.from_url(url, **kwargs)
                return self
            
            async def get(self, key):
                return await self.client.get(key)
            
            async def set(self, key, value, ex=None):
                return await self.client.set(key, value, ex=ex)
            
            async def delete(self, key):
                return await self.client.delete(key)
            
            async def ping(self):
                return await self.client.ping()
            
            async def close(self):
                self.client.close()
                await self.client.wait_closed()
            
            async def lpush(self, key, value):
                return await self.client.lpush(key, value)
            
            async def lrange(self, key, start, end):
                return await self.client.lrange(key, start, end)
            
            async def ltrim(self, key, start, end):
                return await self.client.ltrim(key, start, end)
            
            async def expire(self, key, ttl):
                return await self.client.expire(key, ttl)
        
        redis = RedisWrapper()
        
    except ImportError:
        # Fallback to sync Redis with async wrapper
        import redis as sync_redis
        log.info("Using sync Redis with async wrapper")
        
        class SyncRedisWrapper:
            def __init__(self):
                self.client = None
            
            def from_url(self, url, **kwargs):
                self.client = sync_redis.from_url(url, **kwargs)
                return self
            
            async def get(self, key):
                return self.client.get(key)
            
            async def set(self, key, value, ex=None):
                return self.client.set(key, value, ex=ex)
            
            async def delete(self, key):
                return self.client.delete(key)
            
            async def ping(self):
                return self.client.ping()
            
            async def close(self):
                self.client.close()
            
            async def lpush(self, key, value):
                return self.client.lpush(key, value)
            
            async def lrange(self, key, start, end):
                return self.client.lrange(key, start, end)
            
            async def ltrim(self, key, start, end):
                return self.client.ltrim(key, start, end)
            
            async def expire(self, key, ttl):
                return self.client.expire(key, ttl)
        
        redis = SyncRedisWrapper()

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
            # For sync Redis fallback
            if hasattr(redis, 'Redis'):
                redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                # For async Redis with different constructor
                log.warning("Redis configuration requires redis_url for async client")
                return None
        
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
        # Handle both async and sync ping
        if asyncio.iscoroutinefunction(client.ping):
            await client.ping()
        else:
            client.ping()
        return True
    except Exception as e:
        log.warning(f"Redis ping failed: {e}")
        return False

async def safe_redis_get(key: str) -> Optional[str]:
    """Safe Redis get with fallback"""
    try:
        if await is_redis_available():
            result = await redis_client.get(key)
            return result
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
            result = await redis_client.delete(key)
            return result > 0
    except Exception as e:
        log.debug(f"Redis delete failed for key {key}: {e}")
    return False