# redis/client.py
import logging
from typing import Optional, Any

log = logging.getLogger(__name__)

redis_client = None

def get_redis_client() -> Optional[Any]:
    """Get Redis client with fallback"""
    global redis_client
    
    if redis_client is not None:
        return redis_client
    
    try:
        # Try to import Redis
        import redis as redis_sync
        REDIS_AVAILABLE = True
    except ImportError:
        log.warning("Redis package not installed")
        REDIS_AVAILABLE = False
    
    if not REDIS_AVAILABLE:
        # Create a dummy client
        class DummyRedis:
            async def get(self, key):
                return None
            
            async def set(self, key, value, ex=None):
                return True
            
            async def delete(self, key):
                return True
            
            async def close(self):
                pass
            
            async def lpush(self, key, *values):
                return len(values)
            
            async def lrange(self, key, start, end):
                return []
            
            async def ltrim(self, key, start, end):
                return True
            
            async def expire(self, key, ttl):
                return True
        
        redis_client = DummyRedis()
        log.info("Using dummy Redis client")
        return redis_client
    
    # Real Redis is available
    try:
        import os
        
        # Try async first
        try:
            import redis.asyncio as redis_async
            
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                redis_client = redis_async.from_url(redis_url, decode_responses=True)
            else:
                redis_client = redis_async.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    password=os.getenv("REDIS_PASSWORD"),
                    db=int(os.getenv("REDIS_DB", "0")),
                    decode_responses=True
                )
            
            log.info("Async Redis client initialized")
            
        except ImportError:
            # Fallback to sync Redis
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                redis_client = redis_sync.from_url(redis_url, decode_responses=True)
            else:
                redis_client = redis_sync.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    password=os.getenv("REDIS_PASSWORD"),
                    db=int(os.getenv("REDIS_DB", "0")),
                    decode_responses=True
                )
            
            # Wrap sync methods to be async
            class SyncRedisWrapper:
                def __init__(self, client):
                    self.client = client
                
                async def get(self, key):
                    return self.client.get(key)
                
                async def set(self, key, value, ex=None):
                    return self.client.set(key, value, ex=ex)
                
                async def delete(self, key):
                    return self.client.delete(key)
                
                async def close(self):
                    self.client.close()
                
                async def lpush(self, key, *values):
                    return self.client.lpush(key, *values)
                
                async def lrange(self, key, start, end):
                    return self.client.lrange(key, start, end)
                
                async def ltrim(self, key, start, end):
                    return self.client.ltrim(key, start, end)
                
                async def expire(self, key, ttl):
                    return self.client.expire(key, ttl)
            
            redis_client = SyncRedisWrapper(redis_client)
            log.info("Sync Redis client initialized (wrapped)")
        
        return redis_client
        
    except Exception as e:
        log.error(f"Redis connection failed: {e}")
        
        # Create dummy client as fallback
        class DummyRedis:
            async def get(self, key):
                return None
            
            async def set(self, key, value, ex=None):
                return True
            
            async def delete(self, key):
                return True
            
            async def close(self):
                pass
            
            async def lpush(self, key, *values):
                return len(values)
            
            async def lrange(self, key, start, end):
                return []
            
            async def ltrim(self, key, start, end):
                return True
            
            async def expire(self, key, ttl):
                return True
        
        redis_client = DummyRedis()
        log.info("Using dummy Redis client (fallback)")
        return redis_client